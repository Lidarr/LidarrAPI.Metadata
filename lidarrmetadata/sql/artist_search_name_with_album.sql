SELECT
  artist.gid,
  artist.name,
  artist.comment,
  artist_type.name AS type,
  artist_meta.rating,
  artist_meta.rating_count

FROM artist
  JOIN artist_type ON artist.type = artist_type.id
  JOIN artist_meta ON artist.id = artist_meta.id
  JOIN artist_credit_name ON artist_credit_name.artist = artist.id
  JOIN release_group ON release_group.artist_credit = artist_credit_name.artist_credit
  
WHERE (to_tsvector('mb_simple', artist.name) @@ plainto_tsquery('mb_simple', %(artist)s) 
       OR to_tsvector('mb_simple', artist.sort_name) @@ plainto_tsquery('mb_simple', %(artist)s) 
       OR artist.name = %(artist)s)
AND (to_tsvector('mb_simple', release_group.name) @@ to_tsquery('mb_simple', %(album_query)s))

GROUP BY artist.gid, artist.name, artist.comment, artist_type.name, artist_meta.rating, artist_meta.rating_count

ORDER BY
  CASE WHEN to_tsvector('mb_simple', artist.name) = to_tsvector('mb_simple', %(artist)s) THEN 0 ELSE 1 END,
  CASE WHEN (artist_meta.rating_count * artist_meta.rating) IS NULL THEN 0 ELSE (artist_meta.rating_count * artist_meta.rating) END DESC
