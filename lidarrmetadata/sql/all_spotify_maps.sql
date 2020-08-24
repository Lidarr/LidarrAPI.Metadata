WITH maps AS (

SELECT artist.gid as mbid, substring(url.url from 33) as spotifyid
FROM artist
JOIN l_artist_url ON l_artist_url.entity0 = artist.id
JOIN url ON l_artist_url.entity1 = url.id
WHERE url.url like 'https://open.spotify.com/artist/%'

UNION

SELECT release_group.gid as mbid, substring(url.url from 32) as spotifyid
FROM release_group
JOIN l_release_group_url ON l_release_group_url.entity0 = release_group.id
JOIN url ON l_release_group_url.entity1 = url.id
WHERE url.url LIKE 'https://open.spotify.com/album/%'

UNION

SELECT release_group.gid as mbid, substring(url.url from 32) as spotifyid
FROM release_group
JOIN release ON release.release_group = release_group.id
JOIN l_release_url ON l_release_url.entity0 = release.id
JOIN url ON l_release_url.entity1 = url.id
WHERE url.url LIKE 'https://open.spotify.com/album/%'

)

SELECT DISTINCT ON (spotifyid) spotifyid, mbid
FROM maps
