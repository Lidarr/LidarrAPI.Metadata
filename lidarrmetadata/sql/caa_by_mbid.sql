SELECT unnest(types) AS type,
       release.gid AS release_gid
FROM cover_art_archive.index_listing
       JOIN release ON index_listing.release = release.id
       JOIN release_group ON release.release_group = release_group.id
WHERE release_group.gid = %s