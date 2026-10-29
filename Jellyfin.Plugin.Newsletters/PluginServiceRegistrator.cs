using Jellyfin.Plugin.NewslettersTest.Clients;
using Jellyfin.Plugin.NewslettersTest.Clients.Discord;
using Jellyfin.Plugin.NewslettersTest.Clients.Email;
using Jellyfin.Plugin.NewslettersTest.Clients.Matrix;
using Jellyfin.Plugin.NewslettersTest.Clients.Telegram;
using Jellyfin.Plugin.NewslettersTest.Integrations;
using Jellyfin.Plugin.NewslettersTest.ItemEventNotifier;
using Jellyfin.Plugin.NewslettersTest.Preview;
using Jellyfin.Plugin.NewslettersTest.Scanner;
using Jellyfin.Plugin.NewslettersTest.Shared.Database;
using MediaBrowser.Controller;
using MediaBrowser.Controller.Plugins;
using Microsoft.Extensions.DependencyInjection;

namespace Jellyfin.Plugin.NewslettersTest;

/// <summary>
/// Register newsletter services.
/// </summary>
public class PluginServiceRegistrator : IPluginServiceRegistrator
{
    /// <inheritdoc />
    public void RegisterServices(IServiceCollection serviceCollection, IServerApplicationHost applicationHost)
    {
        // Register the clients
        serviceCollection.AddScoped<IClient, SmtpMailer>();
        serviceCollection.AddScoped<IClient, DiscordWebhook>();
        serviceCollection.AddScoped<IClient, TelegramClient>();
        serviceCollection.AddScoped<IClient, MatrixClient>();

        // Register the item related services
        serviceCollection.AddSingleton<ItemEventManager>();
        serviceCollection.AddSingleton<Scraper>();
        serviceCollection.AddSingleton<PosterImageHandler>();

        // Register the core services
        serviceCollection.AddSingleton<Logger>();
        serviceCollection.AddSingleton<SQLiteDatabase>();

        // Register the integration services
        serviceCollection.AddSingleton<UpcomingMediaService>();

        // Register the newsletter preview service
        serviceCollection.AddSingleton<NewsletterPreviewService>();

        // Register the entry point for item event notifications
        serviceCollection.AddHostedService<ItemEventNotifierEntryPoint>();
    }
}
