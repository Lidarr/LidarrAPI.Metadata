SELECT
  artist.gid,
  array(
    SELECT gid
      FROM artist_gid_redirect
     WHERE artist_gid_redirect.new_id = artist.id
  ) as oldids,
  artist.name,
  artist.sort_name,
  array(
    SELECT name
      FROM artist_alias
     WHERE artist_alias.artist = artist.id
  ) as aliases,
  ended,
  comment,
  artist_type.name AS type,
  artist_meta.rating,
  artist_meta.rating_count
FROM artist
  LEFT JOIN artist_type ON artist.type = artist_type.id
  LEFT JOIN artist_meta ON artist.id = artist_meta.id
WHERE artist.gid = $1
