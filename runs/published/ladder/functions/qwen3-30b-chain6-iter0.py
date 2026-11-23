def score(board, placement):
    lc = placement["lines_cleared"]
    min_h = 20
    for c in range(10):
        for r in range(20):
            if board[r][c]:
                min_h = min(min_h, r)
                break
    holes = 0
    for c in range(10):
        k = None
        for r in range(20):
            if board[r][c]:
                k = r
                break
        if k is not None:
            for r in range(k + 1, 20):
                if not board[r][c]:
                    holes += 1
    return lc * 100 + min_h * 10 - holes * 5 + placement["rotation"] * 0.01
