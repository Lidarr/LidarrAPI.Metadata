-- artist itself updated
SELECT artist.gid
  FROM artist
 WHERE artist.last_updated > $1

       UNION

  -- artist release group updated (basic rg info gets returned as part of artist query)
SELECT DISTINCT artist.gid
  FROM artist
         JOIN artist_credit_name ON artist_credit_name.artist = artist.id
         JOIN release_group ON release_group.artist_credit = artist_credit_name.artist_credit
 WHERE artist_credit_name.position = 0
   AND release_group.last_updated > $1

       UNION

  -- artist release updated (release group status is calculated from releases and returned in artist query)
SELECT DISTINCT artist.gid
  FROM artist
         JOIN artist_credit_name ON artist_credit_name.artist = artist.id
         JOIN release_group ON release_group.artist_credit = artist_credit_name.artist_credit
         JOIN release ON release.release_group = release_group.id
 WHERE artist_credit_name.position = 0
   AND release.last_updated > $1

       UNION

   -- artist links updated
SELECT DISTINCT artist.gid
  FROM artist
         JOIN l_artist_url ON l_artist_url.entity0 = artist.id
         JOIN url ON l_artist_url.entity1 = url.id
  WHERE url.last_updated > $1

       UNION
       
  -- these have been merged into other artists (the other leg will show up artist updated)
SELECT gid
  FROM artist_gid_redirect
 WHERE created > $1
