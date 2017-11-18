SELECT
  artist.gid,
  artist.name,
  artist.sort_name,
  artist.ended,
  comment,
  artist_type.name             AS type,
  array_agg(artist_alias.name) AS aliases
FROM artist
  LEFT JOIN artist_alias ON artist.id = artist_alias.artist
  JOIN artist_type ON artist.type = artist_type.id
WHERE artist.gid = %s
GROUP BY artist.gid, artist.name, artist.sort_name, artist.ended, artist.comment, artist_type.name