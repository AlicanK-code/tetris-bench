def score(board, placement):
    lines = placement["lines_cleared"]
    holes = 0
    for c in range(10):
        has_filled = False
        for r in range(20):
            if board[r][c]:
                has_filled = True
            elif has_filled:
                holes += 1
    sum_heights = 0
    for c in range(10):
        for r in range(19, -1, -1):
            if board[r][c]:
                sum_heights += r
                break
        else:
            sum_heights -= 1
    heights = []
    for c in range(10):
        for r in range(19, -1, -1):
            if board[r][c]:
                heights.append(r)
                break
        else:
            heights.append(-1)
    sum_diffs = 0
    for i in range(9):
        sum_diffs += abs(heights[i] - heights[i+1])
    return lines * 10000 - holes * 100 + sum_heights * 5 - sum_diffs * 10
