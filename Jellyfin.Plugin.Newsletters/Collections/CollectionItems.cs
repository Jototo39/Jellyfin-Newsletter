using System;
using System.Collections.Generic;
using System.Collections.ObjectModel;
using System.Linq;
using Jellyfin.Data.Enums;
using Jellyfin.Plugin.Newsletters.Featured;
using Jellyfin.Plugin.Newsletters.Scanner;
using Jellyfin.Plugin.Newsletters.Shared.Database;
using Jellyfin.Plugin.Newsletters.Shared.Entities;
using Jellyfin.Plugin.Newsletters.Shared.Models;
using MediaBrowser.Controller.Entities;
using MediaBrowser.Controller.Entities.Movies;
using MediaBrowser.Controller.Entities.TV;
using MediaBrowser.Controller.Library;

namespace Jellyfin.Plugin.Newsletters.Collections;

/// <summary>
/// Resolves the collections selected in a client configuration into newsletter entries.
/// </summary>
/// <remarks>
/// Like featured items, collection entries are read live from the library at send time rather
/// than from the queue table, so a section always shows what the collection holds right now.
/// Each selected collection becomes its own section, headed by the collection name.
/// </remarks>
public static class CollectionItems
{
    /// <summary>
    /// The event type collection entries carry through the newsletter pipeline.
    /// </summary>
    public const string EventType = "collection";

    /// <summary>
    /// Builds newsletter entries for the members of the selected collections.
    /// </summary>
    /// <param name="libraryManager">The Jellyfin library manager.</param>
    /// <param name="logger">The logger used to report collections and members that cannot be resolved.</param>
    /// <param name="db">The database searched for an already known poster URL.</param>
    /// <param name="imageHandler">The handler used to look up and fetch poster URLs.</param>
    /// <param name="hostname">The configured server URL, used as the poster URL of last resort.</param>
    /// <param name="selections">The collections selected in the client configuration.</param>
    /// <returns>
    /// One entry per movie, series or episode, with <see cref="JsonFileObj.CollectionName"/> set.
    /// A season is expanded to its episodes. Collections that cannot be found are skipped.
    /// </returns>
    public static Collection<JsonFileObj> Build(
        ILibraryManager libraryManager,
        Logger logger,
        SQLiteDatabase db,
        PosterImageHandler imageHandler,
        string? hostname,
        IEnumerable<CollectionSelection>? selections)
    {
        var entries = new Collection<JsonFileObj>();
        var selected = selections?.Where(s => s is not null).ToList() ?? new List<CollectionSelection>();
        if (selected.Count == 0)
        {
            return entries;
        }

        // The same collection can be matched twice (by ID for one selection, by name for another),
        // so remember which ones are already in.
        var resolvedIds = new HashSet<Guid>();
        List<BoxSet>? allCollections = null;

        foreach (var selection in selected)
        {
            try
            {
                var boxSet = Resolve(selection, libraryManager, logger, ref allCollections);
                if (boxSet is null)
                {
                    logger.Warn($"Collection '{selection.Name}' ({selection.Id}) no longer exists - skipping");
                    continue;
                }

                if (!resolvedIds.Add(boxSet.Id))
                {
                    continue;
                }

                string sectionName = string.IsNullOrWhiteSpace(boxSet.Name) ? selection.Name : boxSet.Name;
                foreach (var member in boxSet.GetLinkedChildren())
                {
                    AddMember(entries, member, sectionName, libraryManager, logger, db, imageHandler, hostname);
                }
            }
            catch (Exception ex)
            {
                logger.Error($"Could not resolve collection '{selection.Name}' ({selection.Id}): {ex.Message}");
            }
        }

        return entries;
    }

    private static BoxSet? Resolve(CollectionSelection selection, ILibraryManager libraryManager, Logger logger, ref List<BoxSet>? allCollections)
    {
        if (Guid.TryParse(selection.Id, out var guid) && libraryManager.GetItemById(guid) is BoxSet byId)
        {
            return byId;
        }

        if (string.IsNullOrWhiteSpace(selection.Name))
        {
            return null;
        }

        // Maintainerr and similar tools delete and recreate their collections, which gives them a
        // new ID. Find the collection again by the name it had when it was selected.
        allCollections ??= libraryManager.GetItemList(new InternalItemsQuery
        {
            IncludeItemTypes = new[] { BaseItemKind.BoxSet },
            Recursive = true
        }).OfType<BoxSet>().ToList();

        var byName = allCollections.FirstOrDefault(c => string.Equals(c.Name, selection.Name, StringComparison.OrdinalIgnoreCase));
        if (byName is not null)
        {
            logger.Debug($"Collection {selection.Id} not found by ID - matched '{selection.Name}' by name instead ({byName.Id:N})");
        }

        return byName;
    }

    private static void AddMember(Collection<JsonFileObj> entries, BaseItem member, string sectionName, ILibraryManager libraryManager, Logger logger, SQLiteDatabase db, PosterImageHandler imageHandler, string? hostname)
    {
        switch (member)
        {
            case Movie or Series:
                // A whole title: no season/episode line, the way a featured title is shown.
                entries.Add(ToCollectionEntry(member, sectionName, libraryManager, logger, db, imageHandler, hostname));
                break;
            case Season season:
                foreach (var episode in GetSeasonEpisodes(season, libraryManager))
                {
                    AddEpisode(entries, episode, sectionName, libraryManager, logger, db, imageHandler, hostname);
                }

                break;
            case Episode episode:
                AddEpisode(entries, episode, sectionName, libraryManager, logger, db, imageHandler, hostname);
                break;
            default:
                logger.Debug($"Skipping '{member.Name}' in collection '{sectionName}' - only movies, series, seasons and episodes are supported");
                break;
        }
    }

    private static void AddEpisode(Collection<JsonFileObj> entries, Episode episode, string sectionName, ILibraryManager libraryManager, Logger logger, SQLiteDatabase db, PosterImageHandler imageHandler, string? hostname)
    {
        // Same rule as the scanner: an episode with no file is not something anyone can watch.
        if (episode.IsVirtualItem)
        {
            return;
        }

        var series = episode.Series;
        if (series is null)
        {
            logger.Debug($"Skipping episode '{episode.Name}' in collection '{sectionName}' - its series could not be found");
            return;
        }

        // Episodes are shown under their series, the way the queue shows them, and the rows of one
        // series are folded into the "Season: X - Eps. Y" lines by ParseSeriesInfo.
        var entry = ToCollectionEntry(series, sectionName, libraryManager, logger, db, imageHandler, hostname);
        entry.Season = episode.ParentIndexNumber ?? episode.Season?.IndexNumber ?? 0;
        entry.Episode = episode.IndexNumber ?? 0;
        entries.Add(entry);
    }

    private static IEnumerable<Episode> GetSeasonEpisodes(Season season, ILibraryManager libraryManager)
    {
        var series = season.Series;
        var query = new InternalItemsQuery
        {
            IncludeItemTypes = new[] { BaseItemKind.Episode },
            IsVirtualItem = false
        };

        // Episodes are not always stored under their season folder, so look them up by season
        // number under the series when there is one.
        if (series is not null && season.IndexNumber.HasValue)
        {
            query.AncestorIds = new[] { series.Id };
            query.ParentIndexNumber = season.IndexNumber.Value;
        }
        else
        {
            query.AncestorIds = new[] { season.Id };
        }

        return libraryManager.GetItemList(query).OfType<Episode>();
    }

    private static JsonFileObj ToCollectionEntry(BaseItem item, string sectionName, ILibraryManager libraryManager, Logger logger, SQLiteDatabase db, PosterImageHandler imageHandler, string? hostname)
    {
        var entry = FeaturedItems.ToEntry(item, libraryManager, logger, db, imageHandler, hostname);
        entry.EventType = EventType;
        entry.CollectionName = sectionName;
        return entry;
    }
}
