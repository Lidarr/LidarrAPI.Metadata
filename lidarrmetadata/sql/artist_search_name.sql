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
  CASE WHEN UPPER(artist.name) = UPPER(%s) THEN 0 ELSE 1 END,
  CASE WHEN (artist_meta.rating_count * artist_meta.rating) IS NULL THEN 0 ELSE (artist_meta.rating_count * artist_meta.rating) END DESC