UsersWatchedStatus = dict[str, str | tuple[str] | dict[str, bool | int]]
UsersWatched = (
    dict[
        frozenset[UsersWatchedStatus],
        dict[
            str,
            list[UsersWatchedStatus]
            | dict[frozenset[UsersWatchedStatus], list[UsersWatchedStatus]],
        ],
    ]
    | list[UsersWatchedStatus]
)
