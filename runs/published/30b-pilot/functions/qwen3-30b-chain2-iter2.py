def score(board, placement):
    holes = 0
    for col in range(10):
        has_filled_above = False
        for row in range(20):
            if board[row][col]:
                has_filled_above = True
            elif has_filled_above:
                holes += 1
    tops = [20] * 10
    for col in range(10):
        for row in range(20):
            if board[row][col]:
                tops[col] = row
                break
    sum_tops = sum(tops)
    unevenness = 0
    for i in range(9):
        unevenness += abs(tops[i] - tops[i+1])
    max_height = 0
    for col in range(10):
        height = 20 - tops[col]
        if height > max_height:
            max_height = height
    lines = placement["lines_cleared"]
    return lines * 50 + sum_tops - holes * 20 - unevenness * 10 - max_height * 3
