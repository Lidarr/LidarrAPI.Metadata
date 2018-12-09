SELECT
  track.id,
  track.gid,
  track.name,
  track.position,
  track.number,
  track.length,
  medium.position    AS medium_position,
  release.gid        AS release_id,
  artist.gid         AS artist_id,
  recording.gid      AS recording_id
FROM track
  JOIN medium ON track.medium = medium.id
  JOIN release ON medium.release = release.id
  JOIN release_group ON release_group.id = release.release_group
  JOIN artist_credit_name ON artist_credit_name.artist_credit = track.artist_credit
  JOIN artist ON artist_credit_name.artist = artist.id
  JOIN recording ON track.recording = recording.id
WHERE release_group.gid = %s AND artist_credit_name.position = 0
