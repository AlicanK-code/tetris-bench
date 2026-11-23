def score(board, placement):
    stack_height = 0
    for row in range(20):
        if any(board[row][col] for col in range(10)):
            stack_height = row
    empty_cells = sum(1 for row in board for cell in row if not cell)
    return float(placement["lines_cleared"] * 10 + (100 - stack_height) + empty_cells * 0.1)
