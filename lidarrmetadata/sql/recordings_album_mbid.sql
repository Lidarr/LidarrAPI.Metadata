SELECT
  recording.gid AS recording_id,
  recording.name,
  recording.length,
  json_agg(json_build_object('release_id', release.gid,
                             'track_number', track.number,
                             'track_position', track.position,
                             'medium_position', medium.position)) AS releases
FROM recording
  INNER JOIN artist ON artist.id = recording.artist_credit
  INNER JOIN track ON track.recording = recording.id
  INNER JOIN medium ON medium.id = track.medium
  INNER JOIN medium_format ON medium_format.id = medium.format
  INNER JOIN release ON release.id = medium.release
  INNER JOIN release_group ON release_group.id = release.release_group
WHERE release_group.gid = %s
GROUP BY recording.gid, recording.name, recording.length