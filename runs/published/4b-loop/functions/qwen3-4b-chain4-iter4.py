def score(board, placement):
    empty_cells = sum(1 for row in board for cell in row if not cell)
    col_heights = [0] * 10
    for j in range(10):
        for i in range(20):
            if board[i][j]:
                col_heights[j] += 1
    max_col_height = max(col_heights)
    top_of_columns = []
    for j in range(10):
        for i in range(20):
            if board[i][j]:
                top_of_columns.append(i)
                break
        else:
            top_of_columns.append(20)
    min_top = min(top_of_columns)
    max_top = max(top_of_columns)
    surface_var = max_top - min_top
    bottom_empty_count = sum(1 for i in range(17, 20) for j in range(10) if not board[i][j])
    lines_cleared = placement["lines_cleared"]
    return float(lines_cleared * 150 + bottom_empty_count * 30 - empty_cells * 25 - max_col_height * 20 - surface_var * 12)
