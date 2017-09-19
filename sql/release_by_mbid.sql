SELECT
  release.gid,
  release.name,
  release_country.date_year AS year,
  release_country.date_month AS month,
  release_country.date_day AS day,
  label.name AS label,
  area.name AS country
FROM release
  LEFT JOIN release_label ON release.id = release_label.release
  LEFT JOIN label ON release_label.label = label.id
  LEFT JOIN release_country ON release.id = release_country.release
  LEFT JOIN country_area ON release_country.country = country_area.area
  LEFT JOIN area ON country_area.area = area.id
WHERE release.gid = %s