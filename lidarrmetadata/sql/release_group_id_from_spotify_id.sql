SELECT release_group.gid
FROM release_group
JOIN release ON release.release_group = release_group.id
JOIN l_release_url ON l_release_url.entity0 = release.id
JOIN url ON l_release_url.entity1 = url.id
WHERE url.url = 'https://open.spotify.com/album/' || $1
LIMIT 1
