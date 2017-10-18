SELECT url.url
FROM url
  -- This doesn't seem to work with a full join?
  JOIN artist ON TRUE
  JOIN l_artist_url ON l_artist_url.entity0 = artist.id AND l_artist_url.entity1 = url.id
WHERE artist.gid = %s