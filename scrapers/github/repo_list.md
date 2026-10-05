# GitHub Repos to Scrape

Verified against the GitHub API on 2026-10-05 (unauthenticated; set
GITHUB_TOKEN for a higher rate limit). Sizes are the API's `size` field
(KiB).

Guards from config.md `## Scrapers`: repos are skipped when they are forks
(`github_skip_forks: true`), archived (`github_skip_archived: false`, so
archived repos are kept), or larger than `github_max_repo_mb` (2048).
Individual files over `github_max_file_mb` (500) are deleted after cloning
and recorded in `_truncated.json`.

## mql5
# homayoun-asghari/mql5-expert-advisors — 0.1 MB — DOWNLOADABLE
homayoun-asghari/mql5-expert-advisors
# geraked/metatrader5 — 10.2 MB — DOWNLOADABLE
geraked/metatrader5
# EA31337/EA31337-classes — 9.5 MB — DOWNLOADABLE
EA31337/EA31337-classes
# Pierre8r/All-MQL5-code — 2.1 MB — DOWNLOADABLE
Pierre8r/All-MQL5-code

# NOTE (2026-10-05): the android_kernel category was deliberately removed.
# Kernel source repositories are NOT cloned — the local LineageOS 23.2 tree
# already contains kernel/samsung/ (including exynos850 and a04s) and that is
# covered by scrapers/lineageos/lineageos_walker.py instead. Previously listed
# and now excluded: LineageOS/android_kernel_samsung_exynos850,
# samsungexynos850/local_manifests, lesdieuxx/android_kernel_a047f_resukisu.

# Discovered by github_search.py on 2026-10-05
## mql5
# 596* · 1.44 MB · Apache-2.0
EarnForex/PositionSizer
# 272* · 0.69 MB · MIT
MegaJoctan/ML5
# 249* · 1140.48 MB · NOASSERTION
francomascareloai/EA_SCALPER_XAUUSD
# 232* · 0.72 MB · BSD-3-Clause
darwinex/dwxconnect
# 211* · 0.54 MB · MIT
xxvw/ICT_Library_MQ5
# 200* · 0.42 MB · Apache-2.0
EarnForex/MarketProfile
# 187* · 2.39 MB · BSD-3-Clause
elrizwiraswara/nyao_scalper_mt5
# 129* · 0.29 MB · MIT
sajidmahamud835/grid-master-pro-mt5-ea
# 124* · 1.2 MB · Apache-2.0
EarnForex/Account-Protector
# 121* · 27.69 MB · GPL-3.0
Narfinsel/Candlestick-Pattern-Scanner
# 120* · 0.23 MB · Apache-2.0
Roffild/RoffildLibrary
# 112* · 5.12 MB · MIT
erlonfs/bad-robot.framework
# 109* · 0.11 MB · GPL-3.0
6alaile/MetaTrader5-to-Telegram
# 106* · 0.05 MB · MIT
vivazzi/JAson
# 101* · 28.52 MB · GPL-3.0
9nix6/Median-and-Turbo-Renko-indicator-bundle
# 85* · 0.04 MB · Apache-2.0
KVignesh122/MT5-SMC-trading-bot
# 84* · 0.1 MB · NOASSERTION
codedpro/mt5-trade-split-manager
# 64* · 0.1 MB · GPL-2.0
Kashu7100/TradingPanel
# 62* · 0.06 MB · NOASSERTION
pipbolt/experts
# 59* · 0.28 MB · Apache-2.0
michaelwade/ModularTradeSystem
# 58* · 26.47 MB · MIT
santiago-cruzlopez/MQL5
# 56* · 0.11 MB · Apache-2.0
EarnForex/News-Trader
# 55* · 0.23 MB · Apache-2.0
EarnForex/AutoTrading-Scheduler
# 46* · 7.37 MB · MIT
e49nana/Algorithmic-trading
# 41* · 0.69 MB · NOASSERTION
NadirAliOfficial/STAR-EA-v11.20
# 40* · 0.06 MB · MIT
jimtin/build-your-own-mt5-ea
# 39* · 0.11 MB · MIT
foeed/FvgGold-EA
# 34* · 0.23 MB · Apache-2.0
EarnForex/Chart-Pattern-Helper
# 28* · 1.29 MB · NOASSERTION
tanzhenxing/EasyMQL
# 28* · 0.02 MB · MIT
NadirAliOfficial/trillex-10s-ea
# 24* · 0.06 MB · Apache-2.0
EarnForex/Amazing
# 23* · 0.07 MB · NOASSERTION
smizxe/mt5-agent-toolkit
# 23* · 0.06 MB · GPL-3.0
scotteza/MQL5-Public
# 22* · 11.35 MB · MIT
mobjoy0/mt5-bridge
# 21* · 0.09 MB · MIT
n30dyn4m1c/crt-turtlesoup-ea
# 21* · 0.03 MB · Apache-2.0
EarnForex/Binario
# 20* · 1.89 MB · MIT
erlonfs/first-candle.bad-robot
# 19* · 0.3 MB · MIT
n30dyn4m1c/gold-pro-scalper
# 19* · 35.31 MB · NOASSERTION
MrOwl1011/Smc_ZOB_CISD
# 17* · 0.56 MB · MIT
erlonfs/box.bad-robot
# 16* · 0.91 MB · MIT
erlonfs/elephant-walk.bad-robot
# 15* · 0.06 MB · Apache-2.0
EarnForex/Adjustable-MA
# 14* · 0.03 MB · Apache-2.0
EarnForex/RSI-EA
# 14* · 8.46 MB · GPL-3.0
handiko/TradingStrategy-Public
# 13* · 1.23 MB · Apache-2.0
SiyabongaDlamini/SmartMoney.MQ5
# 12* · 0.04 MB · MIT
NadirAliOfficial/monsterfx-reliable-trader
# 10* · 0.04 MB · Apache-2.0
EarnForex/myRandom
# 10* · 0.45 MB · MIT
dhruuvsharma/Trading-Strategies
# 8* · 0.02 MB · MIT
NadirAliOfficial/engulfing-zone-ea
# 7* · 0.08 MB · GPL-3.0
DenisZhilkin/MT5-PaperTrade
# 7* · 5.27 MB · NOASSERTION
pedrocarvajal/horizon5-mt
# 6* · 0.11 MB · BSD-3-Clause
BorjaGomezSolorzano/Metatrader-Bridge
