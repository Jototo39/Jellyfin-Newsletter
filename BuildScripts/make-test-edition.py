#!/usr/bin/env python3
"""Turn this checkout into a TEST edition of the plugin that can run next to the official one.

Fork-only, never meant for upstream. Run from the repository root, once, on a throwaway branch:
    python3 BuildScripts/make-test-edition.py

The TEST edition differs from the official plugin in everything the two would otherwise share:
plugin GUID and name, assembly name (so its own config XML), API routes, settings page id,
queue database, newsletter output folder, scheduled task keys, and log prefix.
Its Newsletter task has no default trigger, so it only sends when run by hand.
"""
import pathlib
import sys

TEST_GUID = "46b209f0-7073-4224-a212-cd9dc64efaa4"
OFFICIAL_GUID = "60f478ab-2dd6-4ea0-af10-04d033f75979"
SRC = pathlib.Path("Jellyfin.Plugin.Newsletters")


def edit(rel, pairs):
    path = SRC / rel
    text = path.read_text(encoding="utf-8")
    for old, new, count in pairs:
        found = text.count(old)
        if found != count:
            sys.exit(f"{rel}: expected {count} x {old!r}, found {found}")
        text = text.replace(old, new)
    path.write_text(text, encoding="utf-8")


edit("Jellyfin.Plugin.Newsletters.csproj", [
    ("<RootNamespace>Jellyfin.Plugin.Newsletters</RootNamespace>",
     "<RootNamespace>Jellyfin.Plugin.Newsletters</RootNamespace>\n    <AssemblyName>Jellyfin.Plugin.NewslettersTest</AssemblyName>", 1),
])

edit("Plugin.cs", [
    ('public override string Name => "Newsletters";', 'public override string Name => "Newsletters (TEST)";', 1),
    (OFFICIAL_GUID, TEST_GUID, 1),
    ('config.NewsletterDir = $"{config.TempDirectory}/Newsletters/";', 'config.NewsletterDir = $"{config.TempDirectory}/NewslettersTest/";', 1),
])

ROUTES = {
    "Preview/ClientPreviewController.cs": "Newsletters/ClientPreview",
    "Preview/NewsletterPreviewController.cs": "Newsletters/Preview",
    "Integrations/UpcomingMediaController.cs": "UpcomingMedia",
    "Clients/Email/SmtpMailer.cs": "SmtpMailer",
    "Clients/Discord/DiscordWebhook.cs": "Discord",
    "Clients/Matrix/MatrixClient.cs": "Matrix",
    "Clients/Telegram/TelegramClient.cs": "Telegram",
}
for rel, route in ROUTES.items():
    new_route = "NewslettersTest/" + route.removeprefix("Newsletters/")
    edit(rel, [(f'[Route("{route}")]', f'[Route("{new_route}")]', 1)])

edit("Configuration/configPage.html", [
    ("ApiClient.getUrl('Newsletters/", "ApiClient.getUrl('NewslettersTest/", 3),
    ("ApiClient.getUrl('UpcomingMedia/", "ApiClient.getUrl('NewslettersTest/UpcomingMedia/", 2),
    ("ApiClient.getUrl('SmtpMailer/", "ApiClient.getUrl('NewslettersTest/SmtpMailer/", 1),
    ("ApiClient.getUrl('Discord/", "ApiClient.getUrl('NewslettersTest/Discord/", 1),
    ("ApiClient.getUrl('Matrix/", "ApiClient.getUrl('NewslettersTest/Matrix/", 1),
    ("ApiClient.getUrl('Telegram/", "ApiClient.getUrl('NewslettersTest/Telegram/", 1),
    (OFFICIAL_GUID, TEST_GUID, 1),
    ("NewsletterConfigPage", "NewsletterTestConfigPage", 4),
])

edit("Shared/Database/SQLiteDatabase.cs", [('"/newsletters.db"', '"/newsletters-test.db"', 1)])

edit("ScheduledTasks/NewsletterTask.cs", [
    ('public string Name => "Newsletter";', 'public string Name => "Newsletter (TEST)";', 1),
    ('public string Category => "Newsletters";', 'public string Category => "Newsletters (TEST)";', 1),
    ('public string Key => "Newsletters";', 'public string Key => "NewslettersTest";', 1),
    ("""            yield return new TaskTriggerInfo
            {
                Type = TaskTriggerInfoType.IntervalTrigger,
                IntervalTicks = TimeSpan.FromHours(168).Ticks
            };""", """            // TEST edition: never sends on a schedule, only when run by hand.
            yield break;""", 1),
])

edit("ScheduledTasks/ItemEventTask.cs", [
    ('public string Name => "Newsletter Item Scraper";', 'public string Name => "Newsletter Item Scraper (TEST)";', 1),
    ('public string Category => "Newsletters";', 'public string Category => "Newsletters (TEST)";', 1),
    ('public string Key => "ScanNewsletters";', 'public string Key => "ScanNewslettersTest";', 1),
])

edit("Logger.cs", [('$"[NLP]: ', '$"[NLP-TEST]: ', 1)])

# Jellyfin caches XML serializers by type full name, so identical type names in the two plugins
# collide (the TEST plugin gets the official PluginConfiguration back). Rename the namespace.
import re
NS = re.compile(r"Jellyfin\.Plugin\.Newsletters\b")
for path in SRC.rglob("*.cs"):
    if "obj" in path.parts or "bin" in path.parts:
        continue
    text = path.read_text(encoding="utf-8")
    new = NS.sub("Jellyfin.Plugin.NewslettersTest", text)
    if new != text:
        path.write_text(new, encoding="utf-8")
edit("Jellyfin.Plugin.Newsletters.csproj", [
    ("<RootNamespace>Jellyfin.Plugin.Newsletters</RootNamespace>", "<RootNamespace>Jellyfin.Plugin.NewslettersTest</RootNamespace>", 1),
])

# Jellyfin runs a plugin page's script in the browser's global scope, so the two settings pages
# would share NewsletterConfig (the plugin GUID), loadConfig, saveConfig, discordConfigs... and
# one page could load or save the other plugin's settings. Prefix every global the TEST page defines.
page = SRC / "Configuration/configPage.html"
html = page.read_text(encoding="utf-8")
names = set(re.findall(r"^            (?:var|function) (\w+)", html, re.M)) | {"openTab", "_featuredSearchCache"}
html = html.replace("update' + (configType", "nlTest_update' + (configType")
html = re.sub(r"\b(" + "|".join(sorted(names, key=len, reverse=True)) + r")\b", r"nlTest_\1", html)
page.write_text(html, encoding="utf-8")

# Jellyfin keeps pages already visited in the DOM, hidden, and both settings pages use the same
# element IDs (RadarrConfigList, FeaturedEmoji...). So the TEST page only looks things up inside
# its own page, and while it is hidden it parks its IDs in data-nl-test-id so the official page's
# document-wide lookups cannot find them.
html = page.read_text(encoding="utf-8")
page_sel = "document.querySelector('#NewsletterTestConfigPage"
html = html.replace(page_sel, "NLTEST_PAGE_SEL")
for old, new in (
    ("document.getElementById(", "nlTest_byId("),
    ("document.querySelectorAll(", "nlTest_root().querySelectorAll("),
    ("document.querySelector(", "nlTest_root().querySelector("),
    ("document.getElementsByClassName(", "nlTest_root().getElementsByClassName("),
):
    html = html.replace(old, new)
html = html.replace("NLTEST_PAGE_SEL", page_sel)
helpers = """<script type="text/javascript">
            // TEST edition: scope every lookup to this page (see BuildScripts/make-test-edition.py).
            function nlTest_root() {
                return document.querySelector('#NewsletterTestConfigPage') || document;
            }

            function nlTest_byId(id) {
                return nlTest_root().querySelector('#' + CSS.escape(id));
            }

            function nlTest_parkIds(park) {
                var root = document.querySelector('#NewsletterTestConfigPage');
                if (!root) return;
                if (park) {
                    root.querySelectorAll('[id]').forEach(function (el) { el.setAttribute('data-nl-test-id', el.id); el.removeAttribute('id'); });
                } else {
                    root.querySelectorAll('[data-nl-test-id]').forEach(function (el) { el.id = el.getAttribute('data-nl-test-id'); el.removeAttribute('data-nl-test-id'); });
                }
            }
"""
old = '<script type="text/javascript">\n'
if html.count(old) != 1:
    sys.exit("configPage.html: script tag not found once")
html = html.replace(old, helpers, 1)
old = """                .addEventListener('pageshow', function () {
                    Dashboard.showLoadingMsg();"""
if html.count(old) != 1:
    sys.exit("configPage.html: pageshow handler not found once")
html = html.replace(old, """                .addEventListener('pageshow', function () {
                    nlTest_parkIds(false);
                    Dashboard.showLoadingMsg();""", 1)
old = "            document.querySelector('#NewsletterTestConfigPage')\n                .addEventListener('pageshow'"
if html.count(old) != 1:
    sys.exit("configPage.html: page element lookup not found once")
html = html.replace(old, "            document.querySelector('#NewsletterTestConfigPage')\n                .addEventListener('pagehide', function () { nlTest_parkIds(true); });\n            document.querySelector('#NewsletterTestConfigPage')\n                .addEventListener('viewhide', function () { nlTest_parkIds(true); });\n\n" + old, 1)
page.write_text(html, encoding="utf-8")

print("TEST edition applied. GUID:", TEST_GUID)
