SELECT
  track.name         AS track_name,
  release_group.gid  AS rg_gid,
  release_group.name AS rg_title,
  artist.gid         AS artist_gid,
  artist.name        AS artist_name,
  array_agg(release.gid) AS release_ids
FROM track
  LEFT JOIN medium ON track.medium = medium.id
  LEFT JOIN release ON medium.release = release.id
  LEFT JOIN release_group ON release.release_group = release_group.id
  LEFT JOIN artist ON release_group.artist_credit = artist.id
WHERE UPPER(track.name) LIKE UPPER(%s)
  GROUP BY track.name, release_group.gid, release_group.name, artist.gid, artist.name
ORDER BY
  CASE WHEN UPPER(track.name) = UPPER(%s)
    THEN 0
  ELSE 1 END