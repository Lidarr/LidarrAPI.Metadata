SELECT artist.gid
FROM artist
JOIN l_artist_url ON l_artist_url.entity0 = artist.id
JOIN url ON l_artist_url.entity1 = url.id
WHERE url.url = 'https://open.spotify.com/artist/' || $1
