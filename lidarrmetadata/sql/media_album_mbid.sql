SELECT
  medium.name        AS medium_name,
  medium.position    AS medium_position,
  medium_format.name AS medium_format
FROM medium
  FULL JOIN medium_format ON medium.format = medium_format.id
  JOIN release ON medium.release = release.id
WHERE release.gid = %s