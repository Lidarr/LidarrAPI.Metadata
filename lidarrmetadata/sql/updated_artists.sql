SELECT artist.gid
FROM artist
WHERE artist.last_updated > $1

UNION

SELECT DISTINCT artist.gid
FROM artist
JOIN artist_credit_name ON artist_credit_name.artist = artist.id
JOIN release_group ON release_group.artist_credit = artist_credit_name.artist_credit
WHERE artist_credit_name.position = 0
AND release_group.last_updated > $1
