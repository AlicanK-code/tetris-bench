def score(board, placement):
    empty_cells = 0
    for row in board:
        for cell in row:
            if not cell:
                empty_cells += 1

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

    lines_cleared = placement["lines_cleared"]
    return float(lines_cleared * 100 - empty_cells * 10 - max_col_height * 5 - surface_var * 2)
