SELECT
  artist.gid,
  artist.name,
  comment,
  artist_type.name AS type
FROM artist
  LEFT JOIN artist_type ON artist.type = artist_type.id
WHERE UPPER(artist.name) LIKE UPPER(%s)