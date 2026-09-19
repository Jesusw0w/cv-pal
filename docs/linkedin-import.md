# Getting your LinkedIn profile into CV Pal

CV Pal reviews your LinkedIn profile the same way it reviews your CV — keyword coverage
for recruiter search, completeness per section, and a consistency check against your CV.
To do that it needs a copy of your profile.

**It cannot fetch your profile from a URL.** That is automated access under LinkedIn's
terms, and the account at risk would be yours — a restricted LinkedIn account costs you
the professional network your job search runs on. So you bring the copy; the routes
below take between thirty seconds and three days depending on which you pick.

**In a hurry? Use [Print to PDF](#option-2-print-to-pdf-works-for-everyone).** It works
for every account, takes about thirty seconds, and is good enough for the review.

---

## Option 1: Save to PDF — fastest, if you have it

1. Go to your own profile (click **Me** → **View Profile**).
2. In the top section, click **More** (on some accounts it is labelled **Resources**).
3. Choose **Save to PDF**.
4. Upload the downloaded file to CV Pal.

**Availability is inconsistent.** LinkedIn removed this option in 2025 and brought it
back only for some accounts, so it may simply not be in your menu. It also only works
properly when your profile *and* your account language are set to English — non-English
characters are dropped.

If it is not there, use Option 2. Nothing is lost.

## Option 2: Print to PDF — works for everyone

The universal fallback, and only slightly more work.

1. Open your own profile in a desktop browser.
2. Scroll the whole page to the bottom first, clicking **see more** on your About
   section and any truncated descriptions — anything still collapsed will not be
   printed.
3. Press **Ctrl+P** (**Cmd+P** on a Mac).
4. Under *Destination*, choose **Save as PDF**, then save.
5. Upload the file to CV Pal.

The result contains some LinkedIn navigation text around the edges. That is expected —
CV Pal ignores it.

## Option 3: Copy and paste — instant, least structured

1. Open your profile, expand every **see more**.
2. Select the profile area, copy, and paste it into CV Pal's LinkedIn import box.

Fastest of all, but pasted text loses the section boundaries, so the per-section scoring
is rougher than with a PDF.

## Option 4: Official data export — most complete, slowest

Use this when you want the richest review, and you are not in a hurry.

1. Click **Me** → **Settings & Privacy**.
2. Open **Data Privacy** in the left-hand menu.
3. Under *How LinkedIn uses your data*, click **Get a copy of your data**.
4. Either pick the specific files — **Profile**, **Positions**, **Education**,
   **Skills**, **Recommendations** are the useful ones — or choose the larger archive
   for everything.
5. Click **Request archive** and confirm.
6. LinkedIn emails you a download link. **This can take up to 72 hours**, and the link
   itself expires 72 hours after it arrives, so download it promptly.
7. Upload the ZIP to CV Pal.

This gives structured CSV data rather than page text, so dates, titles and skills come
through exactly rather than being inferred. If you select everything you will get two
emails — the second one has the profile files.

---

## Which should I use?

| | Time | Completeness | Availability |
| --- | --- | --- | --- |
| Save to PDF | ~30 seconds | Good | Some accounts only, English only |
| Print to PDF | ~1 minute | Good | Everyone |
| Copy and paste | ~30 seconds | Basic | Everyone |
| Data export | Up to 3 days | Best | Everyone |

Most people should start with **Print to PDF**, get their review immediately, and
request the data export in the background if they want the more precise version later.

## What the PDF routes cannot give you

Worth knowing before you pick, because it is not obvious and it changes what the review
can tell you. Measured against a real "Save to PDF" export:

| | In the PDF | In the data export |
| --- | --- | --- |
| Name, headline, location | Yes | Yes |
| Roles, employers, dates | Yes | Yes |
| Education | Yes | Yes |
| **Skills** | **Top 3 only** | **All of them** |
| **About / Summary** | Often absent | Yes |
| **Role descriptions** | **None** | Yes |

A one-page profile PDF is about 150 words. Recruiter search filters on skills, so a
profile CV Pal only knows three skills for scores as *thin* on the one section that
decides whether you appear in results at all.

**You do not have to choose.** Import the PDF now for an immediate review, request the
data export, and upload the ZIP when it arrives — CV Pal merges them, and the archive's
data is never overwritten by a later PDF import.

## What CV Pal does with it

The profile is stored alongside your CVs, on your own instance, and is treated as the
sensitive document it is. You can delete it at any time and it is included in your data
export. If you are running in local-only mode, nothing about it reaches any external
service.

Once imported, the **LinkedIn** screen scores each section, measures how findable the
profile is against your target roles, and lists every place it disagrees with your
career profile. It changes neither record — which one is right is your call.

## Keeping your profile URL

CV Pal will ask for your profile URL even though it does not fetch it. It is used to
label the profile, and later by the optional browser extension, which can read the page
you already have open in your own session — giving you the "just point at my profile"
experience without anything being fetched on your behalf.
