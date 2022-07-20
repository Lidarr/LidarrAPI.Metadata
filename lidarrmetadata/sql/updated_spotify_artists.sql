SELECT artist.gid as mbid, substring(url.url from 33) as spotifyid
FROM artist
JOIN l_artist_url on l_artist_url.entity0 = artist.id
JOIN url on l_artist_url.entity1 = url.id
WHERE l_artist_url.last_updated > $1
AND url.url like 'https://open.spotify.com/artist/%'
