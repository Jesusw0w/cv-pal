import { Injectable, computed, inject } from '@angular/core';

import { ApplicationService } from './application.service';
import { CareerProfileService } from './career-profile.service';
import { JobService } from './job.service';
import { PlatformService } from './platform.service';

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

/** A match at or above this score is worth the user's attention first. */
const STRONG_MATCH_SCORE = 85;

@Injectable({ providedIn: 'root' })
export class DashboardService {
  private readonly jobs = inject(JobService);
  private readonly career = inject(CareerProfileService);
  private readonly applied = inject(ApplicationService);
  private readonly platforms = inject(PlatformService);

  /** Strong matches not applied for yet: once applied, a match is no longer waiting. */
  readonly strongMatches = computed(() => {
    const applied = this.applied.appliedPostingIds();
    return this.jobs
      .matches()
      .filter((entry) => entry.match.score >= STRONG_MATCH_SCORE && !applied.has(entry.posting.id));
  });

  /**
   * The pipeline. Each stage is one an application passes out of into the next, so the
   * numbers fall as well as rise — totals that only grow are not a funnel.
   */
  readonly funnel = computed<FunnelStage[]>(() => {
    const byStatus = this.applied.stats().by_status;
    return [
      { label: 'Saved', count: this.jobs.all().length, link: '/jobs' },
      { label: 'Applied', count: byStatus.applied, link: '/applications' },
      { label: 'Interviewing', count: byStatus.interviewing, link: '/applications' },
      { label: 'Offers', count: byStatus.offer, link: '/applications' },
    ];
  });

  /**
   * The one thing worth doing next.
   *
   * Ordered by cost of inaction: an incomplete career profile blocks tailoring
   * altogether, so it comes first; an application already sent is work half done, so a
   * follow-up outranks a new match; a platform showing an old profile costs nothing
   * until a recruiter reads it, so it comes last.
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

    const strong = this.strongMatches();
    if (strong.length > 0) {
      const best = strong[0];
      return {
        headline: `${strong.length} strong match${strong.length > 1 ? 'es' : ''} waiting`,
        detail: `Best is ${best.posting.title} at ${best.posting.company ?? 'an unnamed company'} — ${best.match.score}% match.`,
        cta: 'Review matches',
        link: '/jobs',
        tone: 'opportunity',
      };
    }

    const behind = this.platforms.outdated();
    if (behind.length > 0) {
      return {
        headline: `${behind.length} platform${behind.length > 1 ? 's show' : ' shows'} an older profile`,
        detail: `You changed your profile after last updating ${behind.map((p) => p.name).join(', ')}.`,
        cta: 'Review platforms',
        link: '/applications/platforms',
        tone: 'opportunity',
      };
    }

    return {
      headline: 'Nothing needs your attention',
      detail: 'Your profile is complete and no application is waiting on you.',
      cta: 'Browse matches',
      link: '/jobs',
      tone: 'calm',
    };
  });

  readonly topMatches = computed(() => this.jobs.matches().slice(0, 5));
}
