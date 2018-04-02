SELECT
  artist.gid,
  artist.name,
  comment,
  artist_type.name AS type,
  artist_meta.rating,
  artist_meta.rating_count
FROM artist
  LEFT JOIN artist_type ON artist.type = artist_type.id
  LEFT JOIN artist_meta ON artist.id = artist_meta.id
WHERE UPPER(artist.name) LIKE UPPER(%s)
ORDER BY
  CASE WHEN artist_meta.rating_count IS NULL THEN 1 ELSE 0 END,
  artist_meta.rating_count DESC,
  artist_meta.rating DESC