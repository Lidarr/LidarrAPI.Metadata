SELECT DISTINCT artist.gid
FROM artist
JOIN artist_credit_name ON artist_credit_name.artist = artist.id
JOIN release_group ON artist_credit_name.artist_credit = release_group.artist_credit
