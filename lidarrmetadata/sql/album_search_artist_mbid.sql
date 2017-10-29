SELECT
  release_group.id,
  release_group.gid,
  release_group.name,
  release_group.last_updated
FROM release_group
  JOIN artist ON release_group.artist_credit = artist.id
WHERE artist.gid = %s