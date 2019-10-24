SELECT scored.rgid as rgid, min(scored.score) as score
FROM
(
	SELECT matches.rgid,
	ABS(SUM(medium.track_count) - $1) + (1 - cast(max(matches.matchcount) as float) / sum(medium.track_count)) as score
	FROM
	(
		SELECT release_group.gid as rgid, release.id as releaseid, count(recording.id) as matchcount
		FROM release_group
		JOIN release on release.release_group = release_group.id
		JOIN medium on medium.release = release.id
		JOIN track on track.medium = medium.id
		JOIN recording on recording.id = track.recording
		WHERE recording.gid = ANY($2::uuid[])
		group by release_group.gid, release.id
	)	as matches
	JOIN medium on medium.release = matches.releaseid
	GROUP BY matches.rgid, matches.releaseid
	order by score) as scored
GROUP BY scored.rgid
ORDER BY score
LIMIT 5
