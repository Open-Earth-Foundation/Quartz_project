# 10-City Batch Review

## Scope

- Temporary input used for this audit:
  - `runs/ten_city_input.json`
  - `runs/ten_city_input_tail.json`
- I did not overwrite `NZC.json`; it still remains the 3-city canary file.
- Batch settings used for the review run:
  - `QUARTZ_DISABLE_SDK=1`
  - `QUARTZ_TIMEOUT_SECONDS=20`
  - `QUARTZ_SCRAPE_TIMEOUT_SECONDS=10`
  - `QUARTZ_MAX_SOURCE_URLS_PER_CITY=6`
  - `QUARTZ_MAX_DOCUMENTS_PER_CITY=8`
- Output artifacts:
  - `runs/ten_city_head_registry.json`
  - `runs/ten_city_head_report.json`
  - `runs/ten_city_head_report_review.md`
  - `runs/ten_city_tail_registry.json`
  - `runs/ten_city_tail_report.json`
  - `runs/ten_city_tail_report_review.md`
  - `runs/ten_city_registry_combined.json`
  - `runs/ten_city_summary.json`

## Raw Result

- Combined raw accepted records: `22`
- Combined raw rejected candidates: `48`

Accepted counts by city:

| City | Accepted | First impression |
| --- | ---: | --- |
| Krakow | 2 | usable but incomplete |
| Warsaw | 0 | poor, obvious misses |
| Gdansk | 3 | strongest city in this batch |
| Wroclaw | 3 | noisy, weak precision |
| Lodz | 3 | noisy, weak precision |
| Poznan | 1 | poor, looks wrong |
| Katowice | 2 | mixed |
| Lublin | 3 | mixed, partly generic pages |
| Gdynia | 2 | poor, obvious misses |
| Szczecin | 3 | mixed, noisy |

## Random Link Verification

I manually checked a cross-section of accepted records. Verdicts below are not theoretical; they come from opening the pages and checking whether they look like real, funded climate-related actions from the city ecosystem.

### Clear keeps

1. Krakow
   - `https://krakow.pl/krakow_open_city/krakow_open_city/247661,artykul,zero-emisssions_krakow.html`
   - Verdict: keep
   - Reason: official city page, climate-neutrality portfolio, clearly city-run and climate-related.

2. Gdansk
   - `https://czystemiasto.gdansk.pl/en/life-pom-gozilla-pl/`
   - Verdict: keep
   - Reason: official city waste portal, explicit project page, explicit LIFE co-financing and budget.

3. Katowice
   - `https://katowice.eu/dla-mieszka%C5%84ca/miejskie-centrum-energii/wsparcie-mieszka%C5%84c%C3%B3w/projekt-grantowy-oze`
   - Verdict: likely keep
   - Reason: city domain, OZE grant project, fits funded climate/energy support.

4. Lublin
   - `https://lublin.eu/mieszkancy/srodowisko/powietrze-w-miescie/cieple-mieszkanie/`
   - Verdict: likely keep
   - Reason: official city page for a funded air-quality/heating programme.

5. Szczecin
   - `https://szczecin.eu/pl/zielone-miasto/zefirek-program-wymiany-piecow`
   - Verdict: keep
   - Reason: city official page, climate-relevant, funded furnace-replacement programme.

### Clear false positives or weak accepts

1. Wroclaw
   - `https://www.akcjamiasto.org/wroclawski-program-tramwajowy-2-0/`
   - Verdict: reject
   - Reason: NGO / advocacy site, not an official city source.

2. Wroclaw
   - `https://www.gov.pl/web/climate/energy-projects`
   - Verdict: reject
   - Reason: national ministry landing page, not a Wrocław official project page.

3. Lodz
   - `https://en.erce.unesco.lodz.pl/wdrazanie-planu-gospodarowania-wodami-w-dorzeczu-wisly-na-przykladzie-zlewni-pilicy/`
   - Verdict: reject
   - Reason: research institute page, not a city official source.

4. Poznan
   - `https://slog4.put.poznan.pl/`
   - Verdict: reject
   - Reason: university project site, not a city official source and not a city-funded action page.

5. Gdynia
   - `https://mir.gdynia.pl/?team=dr-marc-silberberger`
   - Verdict: reject
   - Reason: staff profile page, not a funded climate project.

6. Szczecin
   - `http://cudzoziemcy.szczecin.eu/en/category/living-in-szczecin/`
   - Verdict: reject
   - Reason: expat information page, not a climate project.

## Precision Assessment

- Precision is currently too low for a registry that is supposed to end with official city-funded climate projects.
- Sample review suggests precision is below 50%.
- Main failure pattern:
  - external NGO / university / research pages are still getting through
  - national ministry pages are getting through
  - generic programme / funding-source pages are getting through
  - non-project pages are getting through if they mention funding and climate vocabulary

## Omission Checks

I then searched official-looking sources for cities that were suspiciously thin. These are concrete examples the batch missed even though they are plausible climate-related funded actions from city or city-linked official pages.

### Warsaw: clear misses

1. `https://eko.um.warszawa.pl/zywnosc-i-klimat`
   - Food Wave / food-and-climate project
   - official environmental portal
   - explicit funding signal in search result

2. `https://um.warszawa.pl/-/zagraj-w-gre-i-zmien-klimat-na-lepsze`
   - Co-Adapt adaptation project
   - official city site
   - search result explicitly says it uses grant funding

3. `https://um.warszawa.pl/waw/europa/-/budowa-ii-linii-metra-etap-iv`
   - metro expansion with project co-financing
   - official city EU-project page

4. `https://um.warszawa.pl/waw/europa/-/zielone-enklawy-dzielnicy-praga-poludnie`
   - green enclave project
   - official city EU-project page
   - explicit FEnIKS funding in search result

Conclusion for Warsaw: the batch result is not acceptable. Zero accepted is clearly too low.

### Wroclaw: clear misses

1. `https://www.wroclaw.pl/zielony-wroclaw/budujemy-klimat-infrastruktura-i-edukacja-na-rzecz-adaptacji-klimatycznej-wroclawskich-szkol`
   - official city page
   - explicit dofinansowanie
   - strong fit for climate adaptation

Conclusion for Wroclaw: the run found items, but the balance is wrong. It missed a strong official hit and kept obvious non-city pages.

### Lodz: clear misses

1. `https://uml.lodz.pl/ekoportal/eko-wiedza/edukacja/lodzkie-szkoly-dla-klimatu-20/`
   - official city page
   - explicit project funding

2. `https://uml.lodz.pl/ekoportal/klimat/zielen/odtwarzanie-siedlisk-i-ekosystemow/`
   - official city page
   - explicit project funding

3. `https://uml.lodz.pl/ekoportal/klimat/inicjatywy-miedzynarodowe/neest/`
   - official city climate initiative page
   - should likely be reviewed as a candidate

4. `https://mci.uml.lodz.pl/projekty-z-dofinansowaniem/fundusze-europejskie-na-infrastrukture-klimat-srodowisko-2021-2027/`
   - official city “projects with co-financing” page
   - likely a stronger discovery surface than the current accepted UNESCO page

Conclusion for Lodz: obvious official city pages were missed while a non-city institute page was accepted.

### Poznan: clear misses

1. `https://www.poznan.pl/mim/main/fundusze-europejskie-na-infrastrukture-klimat-srodowisko-2021-2027,p,13631,75022,78120.html`
   - official city page
   - explicitly lists city projects with EU co-financing

2. `https://www.poznan.pl/mim/info/news/drugi-etap-tramwaju-na-naramowice-najpierw-projekt,230695.html`
   - official city page
   - explicit FEnIKS funding context

Conclusion for Poznan: current accepted result is not good enough. The city has stronger official project surfaces than the batch captured.

### Gdynia: clear misses

1. `https://www.gdynia.pl/ue/trwajace,8078/infrastruktura-zrownowazonej-mobilnosci-miejskiej-w-gdyni,590866`
   - official city EU-project page
   - explicit FEnIKS co-financing

2. `https://klimat.um.gdynia.pl/post/587701`
   - city climate portal
   - project with EU funding

3. `https://www.gdynia.pl/mieszkaniec/co-nowego,2774/milionowe-dofinansowanie-na-rozbudowe-sieci-kanalizacyjnej-i-modernizacje-oczyszczalni-sciekow,588812`
   - official city news page
   - explicit project funding for wastewater infrastructure

Conclusion for Gdynia: current accepted set is clearly missing better official project pages.

## Overall Completeness Judgment

- Best city in this batch: `Gdansk`
- Probably acceptable but still incomplete: `Krakow`, `Katowice`, `Lublin`
- Not acceptable yet: `Warsaw`, `Wroclaw`, `Lodz`, `Poznan`, `Gdynia`, `Szczecin`

If the product goal is “better to have more than miss some,” the current batch is still underperforming on recall in several important cities. It is also compensating in the wrong way by admitting many false positives.

## Main Problems Observed

1. Source precision is still too loose.
   - city-name-in-domain and municipal wording are enough to let in non-city sources
   - universities, research institutes, NGOs, and national ministry pages still pass too often

2. Discovery ranking is not prioritizing the strongest official city project surfaces.
   - official “EU projects”, “dofinansowanie”, “FEnIKS”, “UE/trwajace”, “ekoportal”, “zielony” pages should rank above generic city-news or external academic pages

3. Verification still accepts pages that are not single project records.
   - funding-source pages
   - generic strategy or SDG pages
   - profiles or category pages

4. Some of the best official city signals are in district pages, transport pages, or dedicated climate portals, and the current search is not consistently surfacing them.

## Recommended Next Fixes

1. Tighten accepted-source policy.
   - prefer city-controlled domains and city-controlled subdomains
   - demote universities, NGOs, research institutes, and national ministry pages unless they are only supporting evidence

2. Add stronger positive query patterns.
   - `umowa o dofinansowanie`
   - `FEnIKS`
   - `UE/trwajace`
   - `projekt dofinansowany`
   - `klimat`
   - `adaptacja`
   - `mobilność`
   - `tramwaj`
   - `OZE`
   - `Ciepłe Mieszkanie`

3. Add city-specific official discovery surfaces as hints.
   - Warsaw: `um.warszawa.pl/waw/europa`, `eko.um.warszawa.pl`
   - Wroclaw: `wroclaw.pl/zielony-wroclaw`
   - Lodz: `uml.lodz.pl/ekoportal`, `mci.uml.lodz.pl/projekty-z-dofinansowaniem`
   - Poznan: `poznan.pl/mim/main/fundusze-europejskie...`
   - Gdynia: `gdynia.pl/ue/trwajace`, `klimat.um.gdynia.pl`

4. Reject obvious non-project pages earlier.
   - staff profiles
   - category listings
   - generic strategy portals
   - generic national funding pages

## Bottom Line

The 10-city run is useful as a stress test, but not yet good enough as a reliable registry batch.

- It does prove that the pipeline can find real official city-funded climate projects.
- It also shows that the current system is still too noisy and still misses obvious official actions in several cities.
- The current behavior is not yet in the “better to have more than miss some” zone; it is currently “miss some and still admit too many wrong pages.”
