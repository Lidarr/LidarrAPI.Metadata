SELECT
  release.gid,
  release.name,
  release.comment,
  release_country.date_year AS year,
  release_country.date_month AS month,
  release_country.date_day AS day,
  label.name AS label,
  area.name AS country,
  medium.name AS medium_name,
  medium.position AS medium_position,
  medium_format.name AS medium_format,
  (SELECT COUNT(*) FROM medium WHERE medium.release = release.id) AS media_count,
  (SELECT SUM(medium.track_count) FROM medium WHERE medium.release = release.id) AS track_count
FROM release
  LEFT JOIN release_label ON release.id = release_label.release
  LEFT JOIN label ON release_label.label = label.id
  LEFT JOIN release_country ON release.id = release_country.release
  LEFT JOIN country_area ON release_country.country = country_area.area
  LEFT JOIN area ON country_area.area = area.id
  LEFT JOIN medium ON medium.release = release.id
  LEFT JOIN medium_format ON medium.format = medium_format.id
WHERE release.gid = %s