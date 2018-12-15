SELECT
  artist.gid,
  artist.name,
  ended,
  comment,
  artist_type.name AS type,
  artist_meta.rating,
  artist_meta.rating_count
FROM artist
  LEFT JOIN artist_type ON artist.type = artist_type.id
  LEFT JOIN artist_meta ON artist.id = artist_meta.id
WHERE artist.gid = %s
