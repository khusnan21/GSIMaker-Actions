import os


class Sdat2img:
    def __init__(self, transfer_list_file, new_data_file, output_image_file):
        print('sdat2img binary - version: 1.3\n')
        self.transfer_list_file = transfer_list_file
        self.new_data_file = new_data_file
        self.output_image_file = output_image_file
        self.list_file = self.parse_transfer_list_file()
        block_size = 4096
        version = next(self.list_file)
        self.version = version
        next(self.list_file)
        versions = {
            1: "Lollipop 5.0",
            2: "Lollipop 5.1",
            3: "Marshmallow 6.x",
            4: "Nougat 7.x / Oreo 8.x / Pie 9.x",
        }
        print("Android {} detected!\n".format(versions.get(version, f'Unknown version {version}!\n')))
        # Don't clobber existing files to avoid accidental data loss
        try:
            output_img = open(self.output_image_file, 'wb')
        except IOError as e:
            if e.errno == 17:
                print(f'Error: the output file "{e.filename}" already exists')
                print('Remove it, rename it, or choose a different file name.')
                return
            else:
                print(e)
                return

        new_data_file = open(self.new_data_file, 'rb')
        max_file_size = 0

        for cmd, block_list in self.list_file:
            max_file_size = max(pair[1] for pair in block_list) * block_size
            for begin, block_all in block_list:
                block_count = block_all - begin
                print(f'Copying {block_count} blocks into position {begin}...')

                # Position output file
                output_img.seek(begin * block_size)

                # Copy one block at a time
                while block_count > 0:
                    output_img.write(new_data_file.read(block_size))
                    block_count -= 1

        # Make file larger if necessary
        if output_img.tell() < max_file_size:
            output_img.truncate(max_file_size)

        output_img.close()
        new_data_file.close()
        print(f'Done! Output image: {os.path.realpath(output_img.name)}')

    @staticmethod
    def rangeset(src):
        src_set = src.split(',')
        num_set = [int(item) for item in src_set]
        if len(num_set) != num_set[0] + 1:
            print(f'Error on parsing following data to rangeset:\n{src}')
            return

        return tuple([(num_set[i], num_set[i + 1]) for i in range(1, len(num_set), 2)])

    def parse_transfer_list_file(self):
        with open(self.transfer_list_file, 'r', encoding='utf-8') as trans_list:
            # First line in transfer list is the version number
            # Second line in transfer list is the total number of blocks we expect to write
            if (version := int(trans_list.readline())) >= 2 and (new_blocks := int(trans_list.readline())):
                # Third line is how many stash entries are needed simultaneously
                trans_list.readline()
                # Fourth line is the maximum number of blocks that will be stashed simultaneously
                trans_list.readline()
            # Subsequent lines are all individual transfer commands
            yield version
            yield new_blocks
            for line in trans_list:
                line = line.split(' ')
                cmd = line[0]
                if cmd == 'new':
                    # if cmd in ['erase', 'new', 'zero']:
                    yield [cmd, self.rangeset(line[1])]
                else:
                    if cmd in ['erase', 'new', 'zero']:
                        print(f'Skipping command {cmd}...')
                        continue
                    # Skip lines starting with numbers, they are not commands anyway
                    if not cmd[0].isdigit():
                        print(f'Command "{cmd}" is not valid.')
                        return
