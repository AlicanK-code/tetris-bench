def score(board, placement):
    filled_cells = sum(cell for row in board for cell in row)
    holes = 200 - filled_cells

    stack_height = -1
    for row in range(19, -1, -1):
        if any(board[row][col] for col in range(10)):
            stack_height = row
            break

    return float(holes * (20 - stack_height) + placement["lines_cleared"])
