using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using Jellyfin.Plugin.NewslettersTest.Clients;
using MediaBrowser.Model.Tasks;

namespace Jellyfin.Plugin.NewslettersTest.ScheduledTasks
{
    /// <summary>
    /// Class RefreshMediaLibraryTask.
    /// </summary>
    public class NewsletterTask(IEnumerable<IClient> clientsInstance, Logger loggerInstance) : IScheduledTask
    {
        private readonly IEnumerable<IClient> clients = clientsInstance;
        private readonly Logger logger = loggerInstance;

        /// <inheritdoc />
        public string Name => "Newsletter (TEST)";

        /// <inheritdoc />
        public string Description => "Send Newsletters to all the specified hooks in plugin";

        /// <inheritdoc />
        public string Category => "Newsletters (TEST)";

        /// <inheritdoc />
        public string Key => "NewslettersTest";

        /// <summary>
        /// Creates the triggers that define when the task will run.
        /// </summary>
        /// <returns>IEnumerable{BaseTaskTrigger}.</returns>
        public IEnumerable<TaskTriggerInfo> GetDefaultTriggers()
        {
            // TEST edition: never sends on a schedule, only when run by hand.
            yield break;
        }

        /// <inheritdoc />
        public async Task ExecuteAsync(IProgress<double> progress, CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            progress.Report(0);
            
            // Call the Notify/Send for each client
            await NotifyAllAsync().ConfigureAwait(false);

            progress.Report(100);
        }

        /// <summary>
        /// Sends newsletters using all configured clients and archives the data if at least one send is successful.
        /// </summary>
        /// <returns>A task representing the asynchronous operation.</returns>
        public async Task NotifyAllAsync()
        {
            bool result = false;
            foreach (var client in clients)
            {
                logger.Debug($"Send triggered for the {client}");
                result |= await client.SendAsync().ConfigureAwait(false);
            }

            // If we the result is True i.e. even if any one client was successful
            // to send the newsletter we'll move the current database
            if (result)
            {
                logger.Debug("Atleast one of the client sent the newsletter. Proceeding forward...");
                clients.First().CopyNewsletterDataToArchive();
            }
            else
            {
                // There could be a case when there is no newsletter to be send. So marking this as Info rather an Error
                // for now.
                logger.Info("None of the client were able to send the newsletter. Please check the plugin configuration.");
            }
        }
    }
}