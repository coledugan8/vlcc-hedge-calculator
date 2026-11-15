# VLCC Freight Hedging Calculator

MARA 342 Maritime Finance group project. A website that forecasts VLCC freight earnings from oil-market drivers and recommends whether a charterer should **lock in a 12-month time charter (hedge)** or **stay on the spot market**. It reproduces the group's Excel model (`VLCC_Tanker_Forecast_Model`) and refreshes its data automatically every day.

## How the live data works

```
FRED (free, public)  ──►  GitHub Actions, daily  ──►  data/data.json  ──►  index.html (GitHub Pages)
```

Every morning a scheduled GitHub job runs `scripts/update_data.py`. It downloads the latest data from FRED, saves it to `data/data.json`, and republishes the site. The page reads that file when it opens, so visitors always see the latest released month. No API keys are needed.

| Series | FRED ID | Used as |
|---|---|---|
| U.S. PPI, Deep Sea Freight Transportation | `PCU483111483111` | Freight rate (**proxy** for VLCC earnings) |
| Brent spot, monthly / daily | `MCOILBRENTEU` / `DCOILBRENTEU` | Model driver / "market now" strip |
| WTI spot, monthly / daily | `MCOILWTICO` / `DCOILWTICO` | Model driver / "market now" strip |

**Important:** the freight index covers all U.S. deep-sea freight, not VLCCs alone, and it is an index rather than $/day. The site scales it so its average equals `anchor_tce` in `config.json` (default $40,000/day). This is an assumption, and the hedge decision is sensitive to it. You can change it in `config.json` or try other values in the site's *Advanced model settings*. Say this in your write-up.

Monthly government data is released with a lag (about one month for oil, two for the freight index). "Live" means the site picks up each new month automatically as soon as it is published.

## Setup (one time, about 10 minutes)

1. **Create a repository.** On github.com, click **New repository**, name it (e.g. `vlcc-hedge-calculator`), make it **Public**, and create it.
2. **Upload the files.** Click **uploading an existing file** and drag in everything from this folder, *including the hidden `.github` folder*. (On a Mac, press Cmd+Shift+. in Finder to show hidden folders.) Commit to `main`.
   - If the `.github` folder won't drag in, create the file by hand: **Add file → Create new file**, name it `.github/workflows/update-data.yml`, and paste in the contents.
3. **Turn on Pages.** Go to **Settings → Pages**. Under **Build and deployment → Source**, choose **GitHub Actions**.
4. **Allow the job to save data.** Go to **Settings → Actions → General → Workflow permissions**, choose **Read and write permissions**, and save.
5. **Run it once.** Go to the **Actions** tab, select **Update data and publish site**, and click **Run workflow**. After about a minute your site is live at `https://<your-username>.github.io/<repo-name>/`.

After that it runs every day by itself. You can always click **Run workflow** to refresh right away.

## Files

| File | What it is |
|---|---|
| `index.html` | The whole website: calculator, charts, hedge map, model check |
| `scripts/update_data.py` | Downloads the data from FRED (Python standard library only) |
| `.github/workflows/update-data.yml` | The daily schedule and publishing job |
| `config.json` | Start month, freight series and the $/day scaling assumption |
| `data/data.json` | Created by the job; don't edit by hand |

## Using real VLCC data instead

If you export real TD3C time-charter-equivalent earnings (for example from Clarksons Shipping Intelligence Network through the TAMU library), use **Try your own data** on the site's *Live data* section. Upload a CSV with the columns `date, vlcc_tce, brent, wti`, the same layout as the workbook's Data sheet.

## Notes

- If FRED is unreachable, the job keeps the previous day's data and still publishes the site.
- Opening `index.html` straight from your computer shows the workbook's simulated data, because browsers block local files from loading `data/data.json`. To preview with live data locally, run `python -m http.server` in this folder after the first update, then open http://localhost:8000.
- GitHub pauses scheduled jobs in repositories with no activity for 60 days. If the data stops updating, open the Actions tab and re-enable the workflow.
