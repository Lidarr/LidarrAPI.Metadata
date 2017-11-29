SELECT
  artist.gid,
  artist.name,
  artist.sort_name,
  ended,
  comment,
  artist_type.name AS type
FROM artist
  LEFT JOIN artist_type ON artist.type = artist_type.id
WHERE artist.gid = %s