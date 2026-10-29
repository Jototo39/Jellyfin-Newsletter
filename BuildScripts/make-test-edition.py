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

print("TEST edition applied. GUID:", TEST_GUID)
