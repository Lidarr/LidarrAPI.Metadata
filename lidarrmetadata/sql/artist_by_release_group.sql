SELECT DISTINCT
  artist.gid
FROM artist
  JOIN artist_credit_name on artist.id = artist_credit_name.artist
  JOIN track on track.artist_credit = artist_credit_name.artist_credit
  JOIN medium on track.medium = medium.id
  JOIN release on medium.release = release.id
  JOIN release_group on release.release_group = release_group.id

WHERE release_group.gid = %s AND artist_credit_name.position = 0
