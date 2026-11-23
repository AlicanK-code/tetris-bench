def score(board, placement):
    surface_height = -1
    for j in range(10):
        col_max = -1
        for i in range(20):
            if board[i][j]:
                if i > col_max:
                    col_max = i
        if col_max > surface_height:
            surface_height = col_max

    tallest_column = 0
    for j in range(10):
        count = 0
        for i in range(20):
            if board[i][j]:
                count += 1
        if count > tallest_column:
            tallest_column = count

    lines_cleared = placement["lines_cleared"]
    return float(lines_cleared * 100 + (20 - surface_height) * 50 + (20 - tallest_column) * 10)
