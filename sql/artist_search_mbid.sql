SELECT
  artist.gid,
  artist.name,
  ended,
  comment,
  artist_type.name AS type
FROM artist
  JOIN artist_type ON artist.type = artist_type.id
WHERE artist.gid = %s