import argparse
import pandas as pd

import utils
from structure import People


def batch_new_people(filename, **kwargs):
	"""
	file format: csv
	name	parent	incash	outcash
	"""
	df = pd.read_csv(filename, dtype={'name': str, 'parent': str, 'incash': float, 'outcash': float})
	df['name'] = df['name'].fillna('')
	df['parent'] = df['parent'].fillna('')
	df.loc[df['parent'] == '', 'parent'] = None
	df['incash'] = df['incash'].fillna(0.)
	df['outcash'] = df['outcash'].fillna(0.)
	update_queue = []

	for idx, row in df.iterrows():
		row_dict = row.to_dict()
		node = People(**row_dict)

		pname = row_dict.get('parent', None)
		if pname is None:
			utils.add_root(node.id)
		else:
			node.parent = utils.ID_MAP[pname]
			pnode = utils.load_people_node(pname, is_id=False)
			pnode.children.append(node.id)
			pnode.dump_people_node()

		node.dump_people_node()
		utils.ID_MAP[node.name] = node.id
		update_queue.append(node.id)

		print('{} added.'.format(row_dict))

	# update metadata
	print('Updating metadata ...')
	for nid in update_queue:
		node = utils.load_people_node(nid)
		node.update_upward()
		node.dump_people_node()


def _payment(payer, amount, ptype, papply=False):
	payer_node = utils.load_people_node(payer, is_id=False)

	if papply:
		def recurse_apply(node):
			node.incash += node.incash_cache
			node.outcash += node.outcash_cache
			node.incash_cache = 0
			node.outcash_cache = 0
			node.dump_people_node()
			if node.parent is not None:
				pnode = utils.load_people_node(node.parent)
				recurse_apply(pnode)

		recurse_apply(payer_node)
		return

	pb = utils.PERCENTAGE[ptype]
	payer_node._outcash_cache += amount

	def recurse_payback(node, pbamount):
		if node.parent is not None:
			l1_node = utils.load_people_node(node.parent)
			l1_node._incash_cache += pb['l1'] * pbamount
			l1_node.dump_people_node()

			if l1_node.parent is not None:
				l2_node = utils.load_people_node(l1_node.parent)
				if l2_node.num_children >= utils.L2_THRESHOLD_NUM_PEOPLE:
					l2_node._incash_cache += pb['l2'] * pbamount
					l2_node.dump_people_node()

			recurse_payback(l1_node, l1_node._incash_cache)

	recurse_payback(payer_node, amount)

	def recurse_cleanup(node):
		node.incash_cache += node._incash_cache
		node.outcash_cache += node._outcash_cache
		node._incash_cache = 0
		node._outcash_cache = 0
		node.dump_people_node()
		if node.parent is not None:
			pnode = utils.load_people_node(node.parent)
			recurse_cleanup(pnode)

	recurse_cleanup(payer_node)


def batch_payment(filename: str, papply=False, **kwargs):
	"""
	file format: csv
	payer	amount	ptype
	"""
	df = pd.read_csv(filename, dtype={'payer': str, 'amount': float, 'ptype': str})
	df['payer'] = df['payer'].fillna('')
	df['amount'] = df['amount'].fillna(0.)
	df['ptype'] = df['ptype'].fillna('')
	for idx, row in df.iterrows():
		row_dict = row.to_dict()
		_payment(**row_dict, papply=papply)
		if not papply:
			print('{} processed.'.format(row_dict))

	if papply:
		export_all()
	else:
		export_all(cache=True)


def export_all(cache=False):
	with open(utils.ID_NUM_FILE, 'r') as f:
		i = int(f.read())
	df_dict = {'id': [], 'name': [], 'incash': [], 'outcash': [], 'netcash': []}
	for nid in range(i):
		node = utils.load_people_node(nid)
		if cache:
			df_dict['id'].append(nid)
			df_dict['name'].append(node.name)
			df_dict['incash'].append(node.incash_cache)
			df_dict['outcash'].append(node.outcash_cache)
			df_dict['netcash'].append(node.incash_cache- node.outcash_cache)
		else:
			df_dict['id'].append(nid)
			df_dict['name'].append(node.name)
			df_dict['incash'].append(node.incash)
			df_dict['outcash'].append(node.outcash)
			df_dict['netcash'].append(node.incash - node.outcash)
	df = pd.DataFrame(df_dict)
	filename = 'output_cache.csv' if cache else 'output.csv'
	with open(filename, 'w') as f:
		df.to_csv(f, index=False, line_terminator='\n')


def reset_all(cache=False):
	with open(utils.ID_NUM_FILE, 'r') as f:
		i = int(f.read())
	for nid in range(i):
		node = utils.load_people_node(nid)
		if not cache:
			node.incash = 0.
			node.outcash = 0.
		node.incash_cache = 0.
		node.outcash_cache = 0.
		node._incash_cache = 0.
		node._outcash_cache = 0.
		node.dump_people_node()


if __name__ == '__main__':
	parser = argparse.ArgumentParser()
	parser.add_argument('func', choices=['people', 'payment', 'apply', 'reset', 'reset_cache'])
	parser.add_argument('--file', type=str)
	args = parser.parse_args()
	if args.func in ['people', 'payment', 'apply'] and args.file is None:
		parser.error('Function {} required --file.'.format(args.func))

	if args.func == 'people':
		batch_new_people(args.file)
	if args.func == 'payment':
		batch_payment(args.file)
	if args.func == 'apply':
		batch_payment(args.file, papply=True)
	if args.func == 'reset_cache':
		reset_all(cache=True)
	if args.func == 'reset':
		reset_all()