# Employment Result Automation Pipeline

Automated scraping and publishing bot that fetches government job updates, admit cards, exam results, answer keys, and syllabus details from `sarkariresult.com.cm`, systematically cleanses and enriches the data, and publishes high-quality, Google AdSense-ready articles to [Employment Result](https://employmentresultin.blogspot.com/).

---

## 🌟 Key Features

1. **Systematic Multi-Category Parsing**:
   - **Latest Jobs**: Captures Important Dates, Application Fees, Age Limits, Vacancy Breakdown, Eligibility Criteria, Selection Process, How-to-Apply Steps, FAQs, and Direct Action Links.
   - **Admit Card & Results**: Focuses on Exam Dates, Result Declaration Dates, Cutoffs, Zone-wise links, and Direct Document Download Buttons.
   - **Answer Key & Syllabus**: Captures Objection Schedules, Exam Patterns, and Question Booklet PDFs.

2. **Google AdSense Monetization Compliance**:
   - **High Word Count (350–700+ words per post)**: Eliminates thin content rejections.
   - **Semantic Heading Hierarchy**: Clear `<h1>`, `<h2>`, and `<h3>` tags for structured readability and SEO ranking.
   - **Competitor & App Scrubbing**: Automatically scrubs competitor footprints (`SarkariResult`, app download prompts, third-party telegram/whatsapp channels) and brands everything under `EMPLOYMENT RESULT`.
   - **Responsive Design**: Wrap-around tables with horizontal scrolling (`overflow-x: auto`) to avoid mobile cutoff on smaller smartphone screens.
   - **Schema-ready FAQs & Step-by-Step Guides**: Built-in Q&A blocks to improve search appearance and user engagement.

3. **Multi-Link Disambiguation**:
   - Accurately distinguishes between separate action links (e.g. *Apply Online (Registration)* vs *Apply Online (Login)*, *Paper 1* vs *Paper 2*, or *Notice (Hindi)* vs *Notice (English)*).

4. **Automated Scheduled Execution**:
   - Powered by GitHub Actions cron schedules running during peak day hours and off-peak night cycles.

---

## 🛠️ Repository Structure

- [`scraper_bot.py`](scraper_bot.py): Main scraper and publisher engine.
- [`fix_old_posts.py`](fix_old_posts.py): Utility script to scan Blogger for old/thin posts and upgrade them to the new systematic format.
- [`published_cache.json`](published_cache.json): Cache to avoid duplicate crawling and publishing.
- [`.github/workflows/auto_draft.yml`](.github/workflows/auto_draft.yml): GitHub Actions automated publish workflow.
- [`.github/workflows/fix_posts.yml`](.github/workflows/fix_posts.yml): GitHub Actions workflow for upgrading old posts on demand.

---

## ⚙️ Configuration & Secrets

The following GitHub Repository Secrets are required:
- `BLOG_ID`: Your Google Blogger Blog ID.
- `GOOGLE_CLIENT_ID`: Google OAuth 2.0 Client ID.
- `GOOGLE_CLIENT_SECRET`: Google OAuth 2.0 Client Secret.
- `GOOGLE_REFRESH_TOKEN`: Google OAuth 2.0 Refresh Token.
