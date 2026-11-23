def score(board, placement):
    lines = placement["lines_cleared"]
    holes = 0
    for c in range(10):
        found = False
        for r in range(20):
            if board[r][c]:
                found = True
                break
        if found:
            for r2 in range(r + 1, 20):
                if not board[r2][c]:
                    holes += 1
    max_height = 0
    for c in range(10):
        count = sum(1 for row in board if row[c])
        if count > max_height:
            max_height = count
    heights = [sum(1 for row in board if row[c]) for c in range(10)]
    bumpiness = 0
    for i in range(9):
        bumpiness += abs(heights[i] - heights[i + 1])
    return lines * 100.0 - holes * 2 - max_height - bumpiness
