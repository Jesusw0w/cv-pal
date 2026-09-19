import { Injectable, computed, inject } from '@angular/core';

import { AnalysisService } from './analysis.service';
import { ApplicationService } from './application.service';
import { CareerProfileService } from './career-profile.service';
import { JobService } from './job.service';

/** A stage of the search pipeline, for the funnel strip. */
export interface FunnelStage {
  label: string;
  count: number;
  /** Route to the screen that acts on this stage. */
  link: string;
}

/** The single most useful thing the user could do right now. */
export interface NextAction {
  headline: string;
  detail: string;
  cta: string;
  link: string;
  /** Drives the accent colour: a problem to fix, or an opportunity to take. */
  tone: 'attention' | 'opportunity' | 'calm';
}

/** Days after which a CV is treated as going stale. */
const STALE_AFTER_DAYS = 90;
/** A match at or above this score is worth the user's attention first. */
const STRONG_MATCH_SCORE = 85;

@Injectable({ providedIn: 'root' })
export class DashboardService {
  private readonly docs = inject(AnalysisService);
  private readonly jobs = inject(JobService);
  private readonly career = inject(CareerProfileService);
  private readonly applied = inject(ApplicationService);

  private readonly daysSince = (iso: string): number =>
    Math.floor((Date.now() - new Date(iso).getTime()) / 86_400_000);

  /** CVs not touched for a while. A stale CV quietly costs opportunities. */
  readonly staleDocuments = computed(() =>
    this.docs
      .documents()
      .filter((cv) => this.daysSince(cv.created_at) > STALE_AFTER_DAYS),
  );

  /** Matches strong enough to be worth reviewing before anything else. */
  readonly strongMatches = computed(() =>
    this.jobs.matches().filter((entry) => entry.match.score >= STRONG_MATCH_SCORE),
  );

  /** Whether there is anything to score at all. */
  readonly hasDocuments = computed(() => this.docs.documents().length > 0);

  /**
   * A profile-health score that decays, so a CV going stale is visible before it
   * costs an opportunity rather than after.
   *
   * An account with no CV scores zero rather than being docked a fixed penalty: the
   * old arithmetic started from a perfect 100 and subtracted 40, so a user who had
   * just signed up and uploaded nothing was told they were at 60/100.
   */
  readonly profileHealth = computed(() => {
    const uploaded = this.docs.documents().length;
    if (uploaded === 0) {
      return 0;
    }
    const stalePenalty = (this.staleDocuments().length / uploaded) * 40;
    return Math.max(0, Math.round(100 - stalePenalty));
  });

  /**
   * The pipeline, which is the shape of a job search.
   *
   * A real funnel now that applications are recorded: each stage is one an application
   * passes *out of* into the next, so the numbers fall as well as rise. The previous
   * version counted saved postings, scored matches and uploaded CVs — three unrelated
   * totals that could only ever grow, arranged to look like a progression.
   */
  readonly funnel = computed<FunnelStage[]>(() => {
    const byStatus = this.applied.stats().by_status;
    return [
      { label: 'Saved', count: this.jobs.all().length, link: '/job-search' },
      { label: 'Applied', count: byStatus.applied, link: '/applications' },
      { label: 'Interviewing', count: byStatus.interviewing, link: '/applications' },
      { label: 'Offers', count: byStatus.offer, link: '/applications' },
    ];
  });

  /**
   * The one thing worth doing next.
   *
   * Ordered by cost of inaction: an incomplete career profile blocks tailoring
   * altogether, so it comes first; a CV an applicant tracking system cannot read wastes
   * every application made with it, so it outranks an unreviewed match, which in turn
   * outranks tidying a draft.
   */
  readonly nextAction = computed<NextAction>(() => {
    // An empty account has not started; the useful answer is the run, not a list.
    if (this.career.isEmpty()) {
      return {
        headline: 'Set up your career profile',
        detail:
          'Upload a CV and CV Pal reads your roles, education and skills out of it. Everything else is generated from that record.',
        cta: 'Start setup',
        link: '/welcome',
        tone: 'opportunity',
      };
    }

    const gaps = this.career.gaps();
    if (gaps.length > 0) {
      return {
        headline: gaps[0].label,
        detail: `${gaps[0].detail} Your profile is ${this.career.completeness()}% ready to tailor from.`,
        cta: 'Open profile',
        link: '/profile',
        tone: gaps.length > 2 ? 'attention' : 'opportunity',
      };
    }

    // Above a stale CV: an application already sent is work that is half done, and a
    // follow-up costs one email. A CV going stale costs nothing until it is next used.
    const quiet = this.applied.needsChasing();
    if (quiet.length > 0) {
      const oldest = quiet[0];
      return {
        headline: `${quiet.length} application${quiet.length > 1 ? 's have' : ' has'} gone quiet`,
        detail: `${oldest.posting.title} at ${oldest.posting.company ?? 'an unnamed company'} has heard nothing for ${oldest.days_since_applied} days.`,
        cta: 'Review applications',
        link: '/applications',
        tone: 'attention',
      };
    }

    const stale = this.staleDocuments();
    if (stale.length > 0) {
      return {
        headline: `${stale.length} CV${stale.length > 1 ? 's have' : ' has'} gone stale`,
        detail: `Not updated in over ${STALE_AFTER_DAYS} days. Applying with an out-of-date CV wastes the application.`,
        cta: 'Review documents',
        link: '/documents',
        tone: 'attention',
      };
    }

    const strong = this.strongMatches();
    if (strong.length > 0) {
      const best = strong[0];
      return {
        headline: `${strong.length} strong match${strong.length > 1 ? 'es' : ''} waiting`,
        detail: `Best is ${best.posting.title} at ${best.posting.company ?? 'an unnamed company'} — ${best.match.score}% match.`,
        cta: 'Review matches',
        link: '/job-search',
        tone: 'opportunity',
      };
    }

    // No CV means nothing downstream can run at all, so it outranks a quiet day.
    if (this.docs.documents().length === 0) {
      return {
        headline: 'Upload a CV to get started',
        detail: 'The ATS and keyword checks need one, and neither needs a language model.',
        cta: 'Go to analysis',
        link: '/analysis',
        tone: 'opportunity',
      };
    }

    return {
      headline: 'Nothing needs your attention',
      detail: 'Your CVs are current and every strong match has been reviewed.',
      cta: 'Browse matches',
      link: '/job-search',
      tone: 'calm',
    };
  });

  readonly recentDocuments = computed(() => this.docs.documents().slice(0, 3));

  readonly jobMatches = computed(() => this.jobs.matches().slice(0, 3));
}
