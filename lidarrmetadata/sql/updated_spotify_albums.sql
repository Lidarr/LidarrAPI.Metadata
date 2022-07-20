WITH maps AS (SELECT release_group.gid as mbid, substring(url.url from 32) as spotifyid
              FROM release_group
                       JOIN release on release.release_group = release_group.id
                       JOIN l_release_url on l_release_url.entity0 = release.id
                       JOIN url on l_release_url.entity1 = url.id
              where l_release_url.last_updated > $1
                and url.url like 'https://open.spotify.com/album/%'

              UNION

              SELECT release_group.gid as mbid, substring(url.url from 32) as spotifyid
              FROM release_group
                       JOIN l_release_group_url on l_release_group_url.entity0 = release_group.id
                       JOIN url on l_release_group_url.entity1 = url.id
              where l_release_group_url.last_updated > $1
                and url.url like 'https://open.spotify.com/album/%')

SELECT DISTINCT ON (spotifyid) spotifyid, mbid
FROM maps
