SELECT
  track.id,
  track.gid,
  track.name,
  track.position,
  track.number,
  track.length,
  medium.name        AS medium_name,
  medium.position    AS medium_position,
  medium_format.name AS medium_format
FROM track
  JOIN medium ON track.medium = medium.id
  JOIN release ON medium.release = release.id
  JOIN medium_format ON medium.format = medium_format.id
WHERE release.gid = % s