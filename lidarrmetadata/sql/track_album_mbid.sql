SELECT
  track.id,
  track.gid,
  track.name,
  track.position,
  track.number,
  track.length,
  medium.position    AS medium_position
FROM track
  JOIN medium ON track.medium = medium.id
  JOIN release ON medium.release = release.id
  LEFT JOIN medium_format ON medium.format = medium_format.id
WHERE release.gid = %s