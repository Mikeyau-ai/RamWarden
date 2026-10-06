# RamWarden: Microsoft Store listing (draft)

Everything Partner Center asks for, ready to paste. Store ID 9MTV6BS7W61S.
Language: English (Australia), plus the same text for English (United States).

---

## Product name
RamWarden

## Short description (≤ 100 characters, shown at the top of the listing)
See what's really using your PC's memory, end the stragglers, and take control of startup apps.

## Description (≤ 10,000 characters)

RamWarden shows you what's really going on inside your PC, then lets you do something about it.

Windows' Task Manager lists hundreds of processes and leaves you to work out which ones matter. RamWarden does that work for you. It groups apps with all the copies they start, so you can see that your browser is really using 3 GB across 40 processes, and it flags the ones that are causing trouble:

• Not responding: windows that have frozen.
• Duplicates: apps running more copies of themselves than they should.
• Suspended, zombie and orphaned processes: leftovers that are stuck, dead, or abandoned by the app that started them.

From there it's one click to end a frozen app, close a misbehaving browser's extra copies while leaving the browser itself running, or ask idle background apps to hand back memory they're not using.

STARTUP APPS
Every program that starts with Windows in one list: the registry run entries, scheduled tasks and Startup folders, all together. Switch any of them off (or back on) without digging through settings. Fewer things starting with Windows means a faster boot.

CLEAR, HONEST AND SAFE
• Windows' own processes are clearly marked and left alone by Trim RAM.
• If something can't be ended, RamWarden tells you why (protected by Windows, owned by your antivirus, needs admin) instead of failing silently.
• Trim RAM reports the real change in memory in use, not an inflated number.
• Light on your PC: a full scan takes a fraction of a second, and it uses almost no CPU while idle.

TRY IT FREE
RamWarden is free to download with a 14-day free trial. The full version is A$14.95, once off, for up to 3 PCs, with all future updates included. During the trial, or once it ends, you can still see everything; only the actions (ending, trimming, changing startup apps) need the full version. Buy and manage licences at sixthdaystudios.com/ramwarden.

Made in Australia by Sixth Day Studios.

## What's new in this version (≤ 1,500 characters)
First release on the Microsoft Store.

## Product features (up to 20, ≤ 200 characters each)
1. Groups each app with every copy it starts and shows the total memory they use together
2. Flags frozen, duplicate, suspended, zombie and orphaned processes
3. End a frozen app, or a browser's extra copies while the browser keeps running
4. Trim RAM: ask idle background apps to hand back unused memory, with the real result shown
5. Every startup app in one list (registry, scheduled tasks, Startup folders), with one-click on/off
6. Explains why a process can't be ended instead of failing silently
7. Fast and light: scans in a fraction of a second, near-zero CPU while idle
8. 14-day free trial; full version A$14.95 once off for up to 3 PCs, all updates included

## Search terms (up to 7)
RAM; memory; task manager; process manager; startup apps; speed up PC; not responding

## Category
Utilities & tools (subcategory: none, or "Performance" if offered)

## URLs
- Website: https://sixthdaystudios.com/ramwarden
- Support contact: https://sixthdaystudios.com/support
- Privacy policy: https://sixthdaystudios.com/privacy

## Copyright and trademark
© 2026 Sixth Day Studios

## Additional licence terms
https://sixthdaystudios.com/terms

## Pricing and availability
- Price: Free (the licence is bought on our website, not through the Store)
- Free trial: No (the Store's own trial option isn't used; the 14-day trial is in the app)
- Markets: all, or start with Australia, New Zealand, United Kingdom, United States, Canada
- Visibility: public

**To confirm when submitting:** Microsoft lets non-game apps use their own payment system. If
Partner Center asks about in-app purchases or third-party payments, answer that the full licence
is sold on our website. Read the wording on the day rather than guessing.

---

## Age rating (IARC questionnaire)
Category: **Utility / productivity app**. Answer **No** to everything:
- violence, fear, sexual content, gambling, crude humour, drugs, alcohol, tobacco
- users can interact or chat with each other
- shares the user's location
- users can buy digital goods inside the app with real money

The app's only link to a purchase opens our website in the browser. Expected rating: 3+ / Everyone.

---

## Restricted capabilities: why RamWarden needs them
Partner Center asks for a reason for each. Paste these.

**runFullTrust**
RamWarden is a desktop process and startup manager. It needs full-trust access to list running
processes, read their memory use, end processes the user chooses, and trim idle processes'
working sets. None of this is possible inside the app sandbox.

**allowElevation**
Some processes and machine-wide startup entries belong to Windows or another user and can only
be ended or changed with administrator rights. RamWarden has an ADMIN button that restarts it
elevated, after the normal Windows UAC prompt, only when the user clicks it.

**unvirtualizedResources (registry and file-system write virtualisation disabled)**
The Startup tab turns startup programs on and off by changing the real per-user startup
registry entries (HKCU\Software\Microsoft\Windows\CurrentVersion\Run and the StartupApproved
keys) and the user's Startup folder. With virtualisation on, Windows would redirect these
changes into a private copy only RamWarden sees, so the user's changes would silently do
nothing. RamWarden changes only startup entries the user chooses.

---

## Screenshots (done, brand/screenshots/, 1586×893 PNG)
1. 1-overview.png: biggest apps first (App total), with the real Trim RAM result in the status bar
2. 2-app-family.png: Chrome and its 15 extra copies selected, End child processes ready
3. 3-startup.png: Startup tab with enabled and disabled entries

## Store logos (ready)
- brand/icon-1024.png: Store logo (1:1)
- brand/store-hero-1920x1080.png: optional hero image
