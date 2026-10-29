namespace Jellyfin.Plugin.NewslettersTest.Shared.Models;

/// <summary>
/// A Jellyfin collection picked to appear as its own section of the newsletter.
/// </summary>
/// <remarks>
/// The name is kept alongside the ID because tools such as Maintainerr delete and recreate
/// their collections, which gives them a new ID. A selection whose ID no longer exists is
/// matched again by name, so it keeps working without being picked again.
/// </remarks>
public sealed class CollectionSelection
{
    /// <summary>
    /// Gets or sets the Jellyfin item ID of the collection.
    /// </summary>
    public string Id { get; set; } = string.Empty;

    /// <summary>
    /// Gets or sets the collection name when it was selected, used when the ID no longer exists.
    /// </summary>
    public string Name { get; set; } = string.Empty;
}
