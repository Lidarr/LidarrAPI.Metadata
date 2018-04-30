SELECT
  track.name         AS track_name,
  track.length       AS track_duration,
  release_group.gid  AS rg_gid,
  release_group.name AS rg_title,
  artist.gid         AS artist_gid,
  artist.name        AS artist_name,
  array_agg(release.gid) AS release_ids,
  recording_meta.rating AS rating,
  recording_meta.rating_count AS rating_count
FROM recording
  LEFT JOIN recording_meta ON recording.id = recording_meta.id
  LEFT JOIN track ON recording.id = track.recording
  LEFT JOIN medium ON track.medium = medium.id
  LEFT JOIN release ON medium.release = release.id
  LEFT JOIN release_group ON release.release_group = release_group.id
  LEFT JOIN artist ON release_group.artist_credit = artist.id
WHERE (to_tsvector('mb_simple', track.name) @@ plainto_tsquery('mb_simple', %s) OR track.name = %s)
  GROUP BY track.name, track.length, release_group.gid, release_group.name, artist.gid, artist.name, recording_meta.rating, recording_meta.rating_count
ORDER BY
  CASE WHEN to_tsvector('mb_simple', track.name) = to_tsvector('mb_simple', %s) THEN 0 ELSE 1 END,
  CASE WHEN (recording_meta.rating_count * recording_meta.rating) IS NULL THEN 0 ELSE (recording_meta.rating_count * recording_meta.rating) END DESC