SELECT artist.gid
  FROM artist
         JOIN artist_gid_redirect ON artist_gid_redirect.new_id = artist.id
 WHERE artist_gid_redirect.gid = $1
