def score(board, placement):
    lines = placement["lines_cleared"]
    holes = 0
    for j in range(10):
        has_filled = False
        for i in range(20):
            if board[i][j]:
                has_filled = True
            elif has_filled:
                holes += 1
    top_rows = []
    for j in range(10):
        top_row = 20
        for i in range(20):
            if board[i][j]:
                top_row = i
                break
        top_rows.append(top_row)
    surface_sum = 0
    for j in range(9):
        surface_sum += abs(top_rows[j] - top_rows[j+1])
    return lines * 1000 - holes * 25 - surface_sum * 5
