def score(board, placement):
    lines_cleared = placement["lines_cleared"]
    empty_cells = 0
    holes = 0
    for row in board:
        for cell in row:
            if not cell:
                empty_cells += 1
    for row in range(20):
        for col in range(10):
            if not board[row][col]:
                up = board[row-1][col] if row > 0 else False
                down = board[row+1][col] if row < 19 else False
                left = board[row][col-1] if col > 0 else False
                right = board[row][col+1] if col < 9 else False
                if up and down and left and right:
                    holes += 1
    return float(lines_cleared * 100 + empty_cells * 10 - holes * 5)
